"""
Resume management handlers for applicants.
Includes resume listing, viewing, editing, statistics and archiving.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx
from datetime import datetime, timezone

from backend.models import User, Resume, get_resume_progress, delete_resume_progress
from shared.constants import UserRole  # удалён ResumeStatus как неиспользуемый
from config.settings import settings
from bot.utils.formatters import format_date  # удалён format_salary_range
from bot.states.resume_states import ResumeCreationStates, ResumeEditStates
from bot.keyboards.common import get_cancel_keyboard, get_main_menu_applicant
from bot.utils.auth import get_user_token
from backend.api.dependencies import create_access_token


router = Router()

MAX_RESUMES_PER_USER = 5


async def build_auth_headers(telegram_id: int, state: FSMContext | None) -> dict:
    """Получить заголовок авторизации. Если state пустой — локально сгенерировать JWT и сохранить в state."""
    token = None
    if state is not None:
        try:
            token = await get_user_token(state)
        except Exception as e:
            logger.warning(f"Cannot get token from state: {e}")
    if not token:
        try:
            user = await User.find_one(User.telegram_id == telegram_id)
            if user and user.is_active:
                payload = {
                    "user_id": str(user.id),
                    "telegram_id": user.telegram_id,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                }
                token = create_access_token(payload)
                if state is not None:
                    # Сохраняем вновь созданный токен в FSM, чтобы последующие запросы использовали его
                    data = await state.get_data()
                    data.update({"token": token, "user_id": str(user.id), "role": payload["role"], "telegram_id": telegram_id})
                    await state.set_data(data)
                    logger.info(f"Fallback token generated and stored for telegram_id={telegram_id}")
            else:
                logger.warning(f"User not found or inactive for fallback token: {telegram_id}")
        except Exception as e:
            logger.error(f"Failed to build fallback token: {e}")
    return {"Authorization": f"Bearer {token}"} if token else {}


# Helper: безопасное обновление сообщения (текст или подпись фото)
async def edit_message_content(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    """Редактировать текст обычного сообщения или подпись фото. Если фото, меняем caption."""
    msg = callback.message
    if getattr(msg, 'photo', None):
        try:
            await msg.edit_caption(caption=text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to edit caption: {e}")
            # Fallback: отправим новое сообщение
            await msg.answer(text, reply_markup=reply_markup)
    else:
        try:
            await msg.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to edit text: {e}")
            # Fallback: отправим новое сообщение
            await msg.answer(text, reply_markup=reply_markup)


# ============ START RESUME CREATION ============

@router.message(F.text == "📝 Создать резюме")
async def start_resume_creation(message: Message, state: FSMContext):
    """Start resume creation process."""
    logger.warning(f"🔥 resume_handlers: '📝 Создать резюме' handler called")
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or not user.has_role(UserRole.APPLICANT):
        await message.answer("Эта функция доступна только для соискателей.")
        return

    # Check resume limit
    existing_resumes = await Resume.find({"user.$id": user.id}).count()
    if existing_resumes >= MAX_RESUMES_PER_USER:
        await message.answer(
            f"📋 <b>Достигнут лимит резюме</b>\n\n"
            f"У тебя уже {existing_resumes} резюме (максимум {MAX_RESUMES_PER_USER}).\n\n"
            "Чтобы создать новое резюме, сначала удали одно из существующих "
            "в разделе «📋 Мои резюме».",
            reply_markup=get_main_menu_applicant()
        )
        return

    # Check for saved draft (progress recovery)
    draft = await get_resume_progress(telegram_id)
    if draft and draft.current_state and draft.full_name:
        # Found saved progress - ask if user wants to continue
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Продолжить", callback_data="resume_draft:continue"),
            InlineKeyboardButton(text="🗑 Начать заново", callback_data="resume_draft:new")
        )

        # Show what was saved
        progress_info = f"• ФИО: {draft.full_name}"
        if draft.city:
            progress_info += f"\n• Город: {draft.city}"
        if draft.phone:
            progress_info += f"\n• Телефон: указан"
        if draft.selected_positions:
            progress_info += f"\n• Должности: {', '.join(draft.selected_positions[:2])}"
        if draft.work_experience:
            progress_info += f"\n• Опыт работы: {len(draft.work_experience)} записей"

        await message.answer(
            "📝 <b>Найден сохранённый прогресс!</b>\n\n"
            f"У тебя есть незавершённое резюме:\n{progress_info}\n\n"
            "Хочешь продолжить с того места, где остановился, "
            "или начать создание резюме заново?",
            reply_markup=builder.as_markup()
        )
        return

    logger.info(f"User {telegram_id} started resume creation")

    await state.set_data({})

    welcome_text = (
        "📝 <b>Создание резюме</b>\n\n"
        "Хммм… 🤔 Вижу, ты у нас впервые.\n"
        "Отлично! Тогда давай создадим твоё резюме с нуля.\n\n"
        "Я задам тебе несколько вопросов, чтобы собрать всю нужную информацию.\n"
        "Не переживай — всё просто и быстро.\n\n"
        "Ты можешь в любой момент:\n"
        "• нажать 🚫 Отменить создание\n"
        "• пропустить необязательные шаги\n\n"
        "Ну что, начнём?\n\n"
        "<b>Как тебя зовут?</b> Напиши ФИО полностью"
    )

    await message.answer(welcome_text, reply_markup=get_cancel_keyboard())
    await state.set_state(ResumeCreationStates.full_name)
    logger.warning(f"🔥 resume_handlers set state to: {await state.get_state()}")


@router.callback_query(F.data == "resume_draft:continue")
async def continue_resume_draft(callback: CallbackQuery, state: FSMContext):
    """Continue resume creation from saved draft."""
    await callback.answer()
    telegram_id = callback.from_user.id

    # Get saved draft
    draft = await get_resume_progress(telegram_id)
    if not draft:
        await callback.message.edit_text(
            "❌ Черновик не найден. Начни создание резюме заново."
        )
        return

    # Restore FSM data from draft
    fsm_data = draft.to_fsm_data()
    await state.set_data(fsm_data)

    # Restore state
    saved_state = draft.current_state
    if saved_state and ":" in saved_state:
        # Extract state class and name
        try:
            await state.set_state(saved_state)
            logger.info(f"Restored state {saved_state} for user {telegram_id}")

            # Show message about restoration and ask for next input
            await callback.message.edit_text(
                "✅ <b>Прогресс восстановлен!</b>\n\n"
                "Продолжай с того места, где остановился.\n"
                "Используй кнопки ниже для навигации.",
                reply_markup=None
            )

            # Trigger the current state handler by sending appropriate message
            # We need to show the prompt for current state
            await _show_current_state_prompt(callback.message, state, saved_state)

        except Exception as e:
            logger.error(f"Error restoring state: {e}")
            # Fallback: start from beginning with data preserved
            await state.set_state(ResumeCreationStates.full_name)
            await callback.message.edit_text(
                "⚠️ Не удалось точно восстановить позицию.\n"
                "Начнём с первого вопроса, но все данные сохранены.\n\n"
                f"<b>Как тебя зовут?</b>\n"
                f"Текущее значение: {draft.full_name or 'не указано'}",
                reply_markup=None
            )
    else:
        # No valid state, start from beginning
        await state.set_state(ResumeCreationStates.full_name)
        await callback.message.edit_text(
            "📝 <b>Продолжаем создание резюме</b>\n\n"
            f"<b>Как тебя зовут?</b>\n"
            f"Текущее значение: {draft.full_name or 'не указано'}",
            reply_markup=None
        )


@router.callback_query(F.data == "resume_draft:new")
async def start_new_resume(callback: CallbackQuery, state: FSMContext):
    """Discard draft and start new resume creation."""
    await callback.answer()
    telegram_id = callback.from_user.id

    # Delete old draft
    await delete_resume_progress(telegram_id)

    # Clear state
    await state.set_data({})

    # Start fresh
    welcome_text = (
        "📝 <b>Создание резюме</b>\n\n"
        "Хорошо! Начинаем с чистого листа.\n\n"
        "Я задам тебе несколько вопросов, чтобы собрать всю нужную информацию.\n"
        "Не переживай — всё просто и быстро.\n\n"
        "Ты можешь в любой момент:\n"
        "• нажать 🚫 Отменить создание\n"
        "• пропустить необязательные шаги\n\n"
        "Ну что, начнём?\n\n"
        "<b>Как тебя зовут?</b> Напиши ФИО полностью"
    )

    await callback.message.edit_text(welcome_text, reply_markup=None)
    await callback.message.answer("Жду твоё ФИО:", reply_markup=get_cancel_keyboard())
    await state.set_state(ResumeCreationStates.full_name)


async def _show_current_state_prompt(message: Message, state: FSMContext, state_name: str):
    """Show appropriate prompt for the current state."""
    from bot.keyboards.common import (
        get_cancel_keyboard,
        get_back_cancel_keyboard,
        get_yes_no_keyboard,
        get_skip_button,
        get_city_selection_keyboard,
    )
    from bot.keyboards.positions import (
        get_position_categories_keyboard,
        get_work_schedule_keyboard,
    )

    # States that need special inline keyboards
    inline_states = {
        "ResumeCreationStates:city": (
            "<b>В каком городе ты находишься?</b>",
            get_city_selection_keyboard()
        ),
        "ResumeCreationStates:position_category": (
            "<b>Какую должность ты ищешь?</b>\nВыбери категорию:",
            get_position_categories_keyboard(show_back=True)
        ),
        "ResumeCreationStates:work_schedule": (
            "<b>Какой график работы тебя интересует?</b>\nМожно выбрать несколько вариантов.",
            get_work_schedule_keyboard([])
        ),
        "ResumeCreationStates:add_work_experience": (
            "<b>Есть ли у тебя опыт работы?</b>",
            get_yes_no_keyboard()
        ),
        "ResumeCreationStates:add_education": (
            "<b>Добавим информацию об образовании?</b>",
            get_yes_no_keyboard()
        ),
        "ResumeCreationStates:add_courses": (
            "<b>Добавить курсы или сертификаты?</b>",
            get_yes_no_keyboard()
        ),
        "ResumeCreationStates:add_languages": (
            "<b>Добавить владение иностранными языками?</b>",
            get_yes_no_keyboard()
        ),
        "ResumeCreationStates:ready_to_relocate": (
            "<b>Готов ли ты переехать в другой город?</b>",
            get_yes_no_keyboard(show_back=True)
        ),
    }

    # States with reply keyboards only
    reply_states = {
        "ResumeCreationStates:full_name": (
            "<b>Как тебя зовут?</b> Напиши ФИО полностью",
            get_cancel_keyboard()
        ),
        "ResumeCreationStates:citizenship": (
            "<b>Укажи своё гражданство</b>\nНапример: Россия",
            get_back_cancel_keyboard()
        ),
        "ResumeCreationStates:birth_date": (
            "<b>Введи свою дату рождения</b>\nФормат: ДД.ММ.ГГГГ (например: 01.01.2000)",
            get_back_cancel_keyboard()
        ),
        "ResumeCreationStates:city_custom": (
            "<b>Напиши название своего города:</b>",
            get_back_cancel_keyboard()
        ),
        "ResumeCreationStates:phone": (
            "<b>Укажи номер телефона</b>\nФормат: +79001234567 или 89001234567",
            get_back_cancel_keyboard()
        ),
        "ResumeCreationStates:photo": (
            "📸 <b>Добавь фото для резюме</b>\nОтправь фотографию.",
            get_cancel_keyboard()
        ),
    }

    # States with skip inline button
    skip_states = {
        "ResumeCreationStates:email": (
            "<b>Укажи свой email</b>\n(или нажми кнопку ниже, чтобы пропустить)",
            get_skip_button()
        ),
        "ResumeCreationStates:desired_salary": (
            "<b>Какую зарплату ты хочешь получать?</b>\nУкажи сумму в рублях (например: 80000)",
            get_skip_button()
        ),
        "ResumeCreationStates:about": (
            "<b>Расскажи немного о себе</b>\nНапример: «Ответственный, пунктуальный»",
            get_skip_button()
        ),
    }

    # First, always send reply keyboard for navigation
    await message.answer(
        "Используй кнопки ниже для навигации:",
        reply_markup=get_back_cancel_keyboard()
    )

    # Check inline states first
    if state_name in inline_states:
        text, inline_kb = inline_states[state_name]
        await message.answer(text, reply_markup=inline_kb)
    elif state_name in reply_states:
        text, reply_kb = reply_states[state_name]
        await message.answer(text, reply_markup=reply_kb)
    elif state_name in skip_states:
        text, skip_kb = skip_states[state_name]
        await message.answer(text, reply_markup=skip_kb)
    else:
        # Unknown state - show generic message
        await message.answer(
            "Продолжай с того места, где остановился.\n"
            "Введи нужные данные или используй кнопки."
        )


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
    if resume.citizenship:
        lines.append(f"🌍 <b>Гражданство:</b> {resume.citizenship}")
    if resume.birth_date:
        try:
            # birth_date is stored as ISO string YYYY-MM-DD
            from datetime import datetime
            birth_dt = datetime.strptime(resume.birth_date, "%Y-%m-%d")
            lines.append(f"🎂 <b>Дата рождения:</b> {birth_dt.strftime('%d.%m.%Y')}")
        except (ValueError, TypeError, AttributeError):
            lines.append(f"🎂 <b>Дата рождения:</b> {resume.birth_date}")
    lines.append(f"📍 <b>Город:</b> {resume.city}")
    if resume.ready_to_relocate:
        lines.append("   ✈️ Готов к переезду")

    # Contacts
    lines.append(f"\n📞 <b>Контакты:</b>")
    if resume.phone:
        lines.append(f"   📱 {resume.phone}")
    if resume.email:
        lines.append(f"   📧 {resume.email}")
    if getattr(resume, 'telegram', None):
        lines.append(f"   ✈️ {resume.telegram}")
    if getattr(resume, 'other_contacts', None):
        lines.append(f"   🔗 {resume.other_contacts}")

    # Desired positions - support multi-positions
    lines.append(f"\n💼 <b>ЖЕЛАЕМЫЕ ДОЛЖНОСТИ</b>")
    desired_positions = getattr(resume, 'desired_positions', None)
    if desired_positions and len(desired_positions) > 0:
        lines.append(f"   Должности: {', '.join(desired_positions)}")
    elif resume.desired_position:
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

    # Courses
    if getattr(resume, 'courses', None):
        lines.append(f"\n🎓 <b>КУРСЫ</b>")
        for course in resume.courses[:5]:
            course_line = course.name
            if course.organization:
                course_line += f", {course.organization}"
            if course.completion_year:
                course_line += f" ({course.completion_year})"
            lines.append(f"   • {course_line}")

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
    if status == "published" or status == "active":
        builder.row(
            InlineKeyboardButton(text="🗄️ В архив", callback_data=f"resume:archive:{resume_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"resume:delete:{resume_id}")
        )
    elif status == "archived":
        builder.row(
            InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"resume:restore:{resume_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"resume:delete:{resume_id}")
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
        await message.answer("Пользователь не найден. Используй /start")
        return

    try:
        resumes = await Resume.find({"user.$id": user.id}).to_list()

        if not resumes:
            await message.answer(
                "📋 <b>Мои резюме</b>\n\n"
                "У тебя пока нет созданных резюме.\n"
                "Создай первое резюме, чтобы начать поиск работы!"
            )
            return

        # Show resume list with inline buttons
        text = f"📋 <b>Мои резюме</b> ({len(resumes)}/{MAX_RESUMES_PER_USER})\n\n"
        text += "Выбери резюме для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for resume in resumes:
            status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
            status_emoji = get_resume_status_emoji(status)

            # Support multi-positions
            desired_positions = getattr(resume, 'desired_positions', None)
            if desired_positions and len(desired_positions) > 0:
                if len(desired_positions) > 2:
                    position = f"{desired_positions[0]} +{len(desired_positions) - 1}"
                else:
                    position = ", ".join(desired_positions)
            else:
                position = resume.desired_position or "Не указана"

            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "-"
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
        await message.answer("Ошибка при загрузке резюме. Попробуй позже.")


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
        await callback.message.edit_text("Пользователь не найден. Используй /start")
        return

    try:
        resumes = await Resume.find({"user.$id": user.id}).to_list()

        if not resumes:
            await callback.message.edit_text(
                "📋 <b>Мои резюме</b>\n\n"
                "У тебя пока нет созданных резюме."
            )
            return

        text = f"📋 <b>Мои резюме</b> ({len(resumes)}/{MAX_RESUMES_PER_USER})\n\n"
        text += "Выбери резюме для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for resume in resumes:
            status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
            status_emoji = get_resume_status_emoji(status)

            # Support multi-positions
            desired_positions = getattr(resume, 'desired_positions', None)
            if desired_positions and len(desired_positions) > 0:
                if len(desired_positions) > 2:
                    position = f"{desired_positions[0]} +{len(desired_positions) - 1}"
                else:
                    position = ", ".join(desired_positions)
            else:
                position = resume.desired_position or "Не указана"

            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "-"
            button_text = f"{status_emoji} {position} | {salary_str} | {resume.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"resume:view:{resume.id}"
                )
            )

        # Заменена логика: если текущее сообщение было фото, удаляем и отправляем новый текст.
        if getattr(callback.message, 'photo', None):
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup())
        else:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error returning to resume list: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке списка резюме.")


@router.callback_query(F.data.startswith("resume:archive:"))
async def archive_resume(callback: CallbackQuery, state: FSMContext):  # добавлен state
    """Archive a resume with confirmation."""
    resume_id = callback.data.split(":")[-1]

    # Show confirmation dialog
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, в архив", callback_data=f"resume:archive_confirm:{resume_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"resume:view:{resume_id}")
    )

    await edit_message_content(
        callback,
        "🗄️ <b>Архивирование резюме</b>\n\n"
        "Ты уверен, что хочешь архивировать это резюме?\n\n"
        "⚠️ Архивированное резюме будет скрыто из поиска и удалено из канала.\n"
        "Ты сможешь восстановить его позже.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resume:archive_confirm:"))
async def confirm_archive_resume(callback: CallbackQuery, state: FSMContext):  # добавлен state
    """Confirm and archive resume."""
    await callback.answer("🗄️ Архивирую резюме...")

    resume_id = callback.data.split(":")[-1]

    try:
        # Call backend API to archive resume
        async with httpx.AsyncClient() as client:
            headers = await build_auth_headers(callback.from_user.id, state)
            if not headers:
                await callback.message.answer("❌ Нет авторизации. Используйте /start")
                return
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}/archive",
                headers=headers
            )

            if response.status_code == 200:
                # Reload resume and update display
                resume = await Resume.get(resume_id)
                text = format_resume_details(resume)
                status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)

                await edit_message_content(
                    callback,
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
async def restore_resume(callback: CallbackQuery, state: FSMContext):  # добавлен state
    """Restore an archived resume."""
    await callback.answer("♻️ Восстанавливаю резюме...")

    resume_id = callback.data.split(":")[-1]

    try:
        # Call backend API to restore resume (publish it again)
        async with httpx.AsyncClient() as client:
            headers = await build_auth_headers(callback.from_user.id, state)
            if not headers:
                await callback.message.answer("❌ Нет авторизации. Используйте /start")
                return
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}/publish",
                headers=headers
            )

            if response.status_code == 200:
                # Reload resume and update display
                resume = await Resume.get(resume_id)
                text = format_resume_details(resume)
                status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)

                await edit_message_content(
                    callback,
                    text,
                    reply_markup=get_resume_management_keyboard(resume_id, status)
                )
                await callback.answer("✅ Резюме восстановлено", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при восстановлении", show_alert=True)

    except Exception as e:
        logger.error(f"Error restoring resume {resume_id}: {e}")
        await callback.answer("❌ Ошибка при восстановлении", show_alert=True)


@router.callback_query(F.data.startswith("resume:delete:"))
async def delete_resume(callback: CallbackQuery):
    """Delete a resume with confirmation."""
    resume_id = callback.data.split(":")[-1]

    # Show confirmation dialog
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"resume:delete_confirm:{resume_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"resume:view:{resume_id}")
    )

    confirmation_text = (
        "🗑 <b>Удаление резюме</b>\n\n"
        "Понял тебя.\n"
        "Если ты действительно хочешь удалить своё резюме, "
        "я могу сделать это прямо сейчас.\n\n"
        "После удаления:\n"
        "• работодатели больше не смогут его видеть\n"
        "• оно исчезнет из раздела «Мои резюме»\n"
        "• восстановить его будет невозможно, но можно создать новое\n\n"
        "<b>Подтвердить удаление?</b>"
    )

    # Try to edit text, if fails (photo message) - delete and send new
    try:
        await callback.message.edit_text(
            confirmation_text,
            reply_markup=builder.as_markup()
        )
    except Exception:
        # Message has photo, delete it and send new text message
        await callback.message.delete()
        await callback.message.answer(
            confirmation_text,
            reply_markup=builder.as_markup()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("resume:delete_confirm:"))
async def confirm_delete_resume(callback: CallbackQuery):
    """Confirm and delete resume."""
    await callback.answer("🗑 Удаляю резюме...")

    resume_id = callback.data.split(":")[-1]

    try:
        # Call backend API to delete resume
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{settings.api_url}/resumes/{resume_id}"
            )

            if response.status_code == 204:
                # Show back to list button
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="📋 Мои резюме", callback_data="resume:list")
                )

                success_text = (
                    "✅ <b>Резюме удалено</b>\n\n"
                    "Резюме было удалено из базы и из канала."
                )

                # Try to edit text, if fails - delete and send new
                try:
                    await callback.message.edit_text(
                        success_text,
                        reply_markup=builder.as_markup()
                    )
                except Exception:
                    await callback.message.delete()
                    await callback.message.answer(
                        success_text,
                        reply_markup=builder.as_markup()
                    )

                logger.info(f"Resume {resume_id} deleted by user {callback.from_user.id}")
            else:
                await callback.answer("❌ Ошибка при удалении", show_alert=True)

    except Exception as e:
        logger.error(f"Error deleting resume {resume_id}: {e}")
        await callback.answer("❌ Ошибка при удалении", show_alert=True)


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
            Response.applicant == user.id
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

def get_edit_sections_keyboard(resume_id: str) -> InlineKeyboardMarkup:
    """Создать клавиатуру с разделами для редактирования."""
    builder = InlineKeyboardBuilder()

    # Личные данные
    builder.row(
        InlineKeyboardButton(text="👤 Личные данные", callback_data=f"edit_resume_field:personal:{resume_id}")
    )
    # Должность и зарплата
    builder.row(
        InlineKeyboardButton(text="💼 Должность", callback_data=f"edit_resume_field:position:{resume_id}"),
        InlineKeyboardButton(text="💰 Зарплата", callback_data=f"edit_resume_field:salary:{resume_id}")
    )
    # Опыт и образование
    builder.row(
        InlineKeyboardButton(text="💼 Опыт работы", callback_data=f"edit_resume_field:experience:{resume_id}"),
        InlineKeyboardButton(text="🎓 Образование", callback_data=f"edit_resume_field:education:{resume_id}")
    )
    # Навыки и курсы
    builder.row(
        InlineKeyboardButton(text="🎯 Навыки", callback_data=f"edit_resume_field:skills:{resume_id}"),
        InlineKeyboardButton(text="📜 Курсы", callback_data=f"edit_resume_field:courses:{resume_id}")
    )
    # Языки и фото
    builder.row(
        InlineKeyboardButton(text="🌍 Языки", callback_data=f"edit_resume_field:languages:{resume_id}"),
        InlineKeyboardButton(text="📸 Фото", callback_data=f"edit_resume_field:photo:{resume_id}")
    )
    # Контакты и о себе
    builder.row(
        InlineKeyboardButton(text="📞 Контакты", callback_data=f"edit_resume_field:contacts:{resume_id}"),
        InlineKeyboardButton(text="📝 О себе", callback_data=f"edit_resume_field:about:{resume_id}")
    )
    # Отмена
    builder.row(
        InlineKeyboardButton(text="❌ Готово", callback_data=f"resume:view:{resume_id}")
    )

    return builder.as_markup()


@router.callback_query(F.data.startswith("resume:edit:"))
async def start_resume_edit(callback: CallbackQuery, state: FSMContext):
    """Start resume editing - show field selection menu."""
    await callback.answer()

    resume_id = callback.data.split(":")[-1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = await build_auth_headers(callback.from_user.id, state)
            if not headers:
                await callback.message.answer("❌ Нет авторизации. Используй /start")
                return
            response = await client.get(
                f"{settings.api_url}/resumes/{resume_id}",
                headers=headers
            )

            if response.status_code != 200:
                await callback.message.answer("❌ Резюме не найдено")
                return

            resume = response.json()

            # Save resume to state
            await state.update_data(editing_resume_id=resume_id, resume_data=resume)

            # Show field selection menu
            text = (
                "✏️ <b>Хорошо! Давай внесём изменения в твоё резюме.</b>\n\n"
                "Выбери, что именно хочешь исправить, и я всё обновлю.\n\n"
                "Ты можешь изменить любую часть:\n"
                "• личные данные\n"
                "• опыт работы\n"
                "• образование\n"
                "• навыки\n"
                "• фото\n"
                "• желаемую должность и зарплату\n\n"
                "<b>Готов? Выбери раздел:</b>"
            )

            await edit_message_content(callback, text, reply_markup=get_edit_sections_keyboard(resume_id))
            await state.set_state(ResumeEditStates.select_section)

    except Exception as e:
        logger.error(f"Error starting resume edit: {e}")
        await callback.message.answer("❌ Ошибка при загрузке резюме")


@router.callback_query(ResumeEditStates.select_section, F.data.startswith("edit_resume_field:"))
async def select_resume_field(callback: CallbackQuery, state: FSMContext):
    """Handle field selection for editing."""
    await callback.answer()

    parts = callback.data.split(":")
    field = parts[1]
    resume_id = parts[2]

    await state.update_data(editing_field=field, editing_resume_id=resume_id)

    # Show input prompt based on field type
    prompts = {
        "salary": "💰 <b>Желаемая зарплата</b>\n\nВведи желаемую зарплату (только число):\nПример: 50000",
        "city": "📍 <b>Город</b>\n\nВведи город:",
        "position": "💼 <b>Должность</b>\n\nВведи желаемую должность:",
        "skills": "🎯 <b>Навыки</b>\n\nВведи навыки через запятую:\nПример: Работа с кассой, Знание меню, Сервис",
        "phone": "📞 <b>Телефон</b>\n\nВведи номер телефона:\nПример: +7 900 123-45-67",
        "email": "✉️ <b>Email</b>\n\nВведи email:",
        "about": "📝 <b>О себе</b>\n\nНапиши информацию о себе:",
        "photo": "📸 <b>Фото</b>\n\nОтправь новое фото для резюме:",
        "personal": (
            "👤 <b>Личные данные</b>\n\n"
            "Что хочешь изменить?\n"
            "Выбери из списка:"
        ),
        "contacts": (
            "📞 <b>Контакты</b>\n\n"
            "Что хочешь изменить?\n"
            "Выбери из списка:"
        ),
        "experience": (
            "💼 <b>Опыт работы</b>\n\n"
            "Чтобы изменить опыт работы, напиши в свободной форме:\n"
            "Компания, должность, период работы.\n\n"
            "Например: Ресторан Восход, официант, 2020-2023"
        ),
        "education": (
            "🎓 <b>Образование</b>\n\n"
            "Напиши информацию об образовании:\n"
            "Уровень, учебное заведение.\n\n"
            "Например: Высшее, МГУ"
        ),
        "courses": (
            "📜 <b>Курсы</b>\n\n"
            "Напиши информацию о курсах:\n"
            "Название курса, организатор, год.\n\n"
            "Например: Бариста-профи, Кофемания, 2022"
        ),
        "languages": (
            "🌍 <b>Языки</b>\n\n"
            "Напиши языки и уровень владения:\n\n"
            "Например: Английский B2, Французский A1"
        ),
    }

    prompt = prompts.get(field, "Введи новое значение:")

    # Для полей с подменю создаём дополнительные кнопки
    kb = InlineKeyboardBuilder()

    if field == "personal":
        kb.row(
            InlineKeyboardButton(text="👤 ФИО", callback_data=f"edit_resume_subfield:full_name:{resume_id}"),
            InlineKeyboardButton(text="🌍 Гражданство", callback_data=f"edit_resume_subfield:citizenship:{resume_id}")
        )
        kb.row(
            InlineKeyboardButton(text="🎂 Дата рождения", callback_data=f"edit_resume_subfield:birth_date:{resume_id}"),
            InlineKeyboardButton(text="📍 Город", callback_data=f"edit_resume_subfield:city:{resume_id}")
        )
        kb.row(
            InlineKeyboardButton(text="✈️ Готовность к переезду", callback_data=f"edit_resume_subfield:relocate:{resume_id}")
        )
        kb.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"resume:edit:{resume_id}")
        )
        await edit_message_content(callback, prompt, reply_markup=kb.as_markup())
        return

    if field == "contacts":
        kb.row(
            InlineKeyboardButton(text="📞 Телефон", callback_data=f"edit_resume_subfield:phone:{resume_id}"),
            InlineKeyboardButton(text="✉️ Email", callback_data=f"edit_resume_subfield:email:{resume_id}")
        )
        kb.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"resume:edit:{resume_id}")
        )
        await edit_message_content(callback, prompt, reply_markup=kb.as_markup())
        return

    # Обычные поля с текстовым вводом
    kb.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"resume:edit:{resume_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"resume:view:{resume_id}")
    )

    await edit_message_content(callback, prompt, reply_markup=kb.as_markup())
    await state.set_state(ResumeEditStates.edit_value)


@router.callback_query(ResumeEditStates.select_section, F.data.startswith("edit_resume_subfield:"))
async def select_resume_subfield(callback: CallbackQuery, state: FSMContext):
    """Handle subfield selection for personal/contacts editing."""
    await callback.answer()

    parts = callback.data.split(":")
    subfield = parts[1]
    resume_id = parts[2]

    await state.update_data(editing_field=subfield, editing_resume_id=resume_id)

    # Prompts for subfields
    prompts = {
        "full_name": "👤 <b>ФИО</b>\n\nВведи полное имя:",
        "citizenship": "🌍 <b>Гражданство</b>\n\nВведи гражданство:\nНапример: Россия",
        "birth_date": "🎂 <b>Дата рождения</b>\n\nВведи дату в формате ДД.ММ.ГГГГ:\nНапример: 15.03.1995",
        "city": "📍 <b>Город</b>\n\nВведи город:",
        "relocate": "✈️ <b>Готовность к переезду</b>\n\nГотов ли ты к переезду?",
        "phone": "📞 <b>Телефон</b>\n\nВведи номер телефона:\nНапример: +7 900 123-45-67",
        "email": "✉️ <b>Email</b>\n\nВведи email:",
    }

    prompt = prompts.get(subfield, "Введи новое значение:")

    kb = InlineKeyboardBuilder()

    # Для relocate делаем кнопки Да/Нет
    if subfield == "relocate":
        kb.row(
            InlineKeyboardButton(text="✅ Да", callback_data=f"edit_resume_relocate:yes:{resume_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"edit_resume_relocate:no:{resume_id}")
        )
        kb.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_resume_field:personal:{resume_id}")
        )
        await edit_message_content(callback, prompt, reply_markup=kb.as_markup())
        return

    kb.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"resume:edit:{resume_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"resume:view:{resume_id}")
    )

    await edit_message_content(callback, prompt, reply_markup=kb.as_markup())
    await state.set_state(ResumeEditStates.edit_value)


@router.callback_query(ResumeEditStates.select_section, F.data.startswith("edit_resume_relocate:"))
async def toggle_relocate(callback: CallbackQuery, state: FSMContext):
    """Toggle relocate setting."""
    await callback.answer()

    parts = callback.data.split(":")
    value = parts[1] == "yes"
    resume_id = parts[2]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = await build_auth_headers(callback.from_user.id, state)
            if not headers:
                await callback.message.answer("❌ Нет авторизации. Используй /start")
                return
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}",
                json={"ready_to_relocate": value},
                headers=headers
            )

            if response.status_code == 200:
                status = "готов к переезду" if value else "не готов к переезду"
                await show_edit_continue_prompt(callback, state, resume_id, f"Статус: {status}")
            else:
                await callback.answer("❌ Ошибка обновления", show_alert=True)

    except Exception as e:
        logger.error(f"Error updating relocate: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


async def show_edit_continue_prompt(callback: CallbackQuery, state: FSMContext, resume_id: str, updated_text: str):
    """Show prompt asking if user wants to edit more fields."""
    text = (
        f"✅ {updated_text}\n\n"
        "<b>Ещё что-то хочешь исправить?</b>\n"
        "Выбери раздел или нажми «Готово»:"
    )

    await edit_message_content(callback, text, reply_markup=get_edit_sections_keyboard(resume_id))
    await state.set_state(ResumeEditStates.select_section)


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
            headers = await build_auth_headers(message.from_user.id, state)
            if not headers:
                await message.answer("❌ Нет авторизации. Используй /start")
                return
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}",
                json=update_data,
                headers=headers
            )

            if response.status_code == 200:
                # Show continue prompt
                text = (
                    "✅ Фото успешно обновлено!\n\n"
                    "<b>Ещё что-то хочешь исправить?</b>\n"
                    "Выбери раздел или нажми «Готово»:"
                )
                await message.answer(text, reply_markup=get_edit_sections_keyboard(resume_id))
                await state.set_state(ResumeEditStates.select_section)
                logger.info(f"Resume {resume_id} photo updated")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await message.answer(f"❌ Ошибка обновления: {error_detail}")
                await state.clear()

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
        await message.answer("❌ Пожалуйста, отправь фотографию, а не текст")
        return

    new_value = message.text.strip()

    if not resume_id or not field:
        await message.answer("❌ Ошибка: данные редактирования потеряны")
        await state.clear()
        return

    # Validate and prepare data
    update_data = {}
    field_name = ""  # Название поля для отображения

    try:
        import re

        if field == "salary":
            numbers = re.findall(r'\d+', new_value.replace(',', '').replace(' ', ''))
            if numbers:
                update_data["desired_salary"] = int(numbers[0])
                field_name = f"Зарплата: {numbers[0]} руб."
            else:
                await message.answer("❌ Некорректная зарплата. Попробуй ещё раз:")
                return

        elif field == "city":
            update_data["city"] = new_value
            field_name = f"Город: {new_value}"

        elif field == "position":
            update_data["desired_position"] = new_value
            field_name = f"Должность: {new_value}"

        elif field == "skills":
            skills = [s.strip() for s in new_value.split(",") if s.strip()]
            update_data["skills"] = skills
            field_name = f"Навыки обновлены ({len(skills)} шт.)"

        elif field == "phone":
            update_data["phone"] = new_value
            field_name = f"Телефон: {new_value}"

        elif field == "email":
            if "@" not in new_value or "." not in new_value:
                await message.answer("❌ Некорректный email. Попробуй ещё раз:")
                return
            update_data["email"] = new_value
            field_name = f"Email: {new_value}"

        elif field == "about":
            update_data["about"] = new_value
            field_name = "О себе обновлено"

        elif field == "full_name":
            update_data["full_name"] = new_value
            field_name = f"ФИО: {new_value}"

        elif field == "citizenship":
            update_data["citizenship"] = new_value
            field_name = f"Гражданство: {new_value}"

        elif field == "birth_date":
            # Validate date format DD.MM.YYYY
            date_match = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', new_value)
            if date_match:
                day, month, year = date_match.groups()
                # Convert to ISO format YYYY-MM-DD
                update_data["birth_date"] = f"{year}-{month}-{day}"
                field_name = f"Дата рождения: {new_value}"
            else:
                await message.answer("❌ Некорректный формат даты. Используй ДД.ММ.ГГГГ\nНапример: 15.03.1995")
                return

        elif field == "experience":
            # Parse experience: Company, position, period
            # Это простой парсинг, можно улучшить
            update_data["work_experience"] = [{
                "company": new_value.split(",")[0].strip() if "," in new_value else new_value,
                "position": new_value.split(",")[1].strip() if "," in new_value and len(new_value.split(",")) > 1 else "",
                "start_date": None,
                "end_date": None,
            }]
            field_name = "Опыт работы обновлён"

        elif field == "education":
            # Parse education: Level, institution
            parts = [p.strip() for p in new_value.split(",")]
            update_data["education"] = [{
                "level": parts[0] if parts else new_value,
                "institution": parts[1] if len(parts) > 1 else "",
                "faculty": None,
                "graduation_year": None,
            }]
            field_name = "Образование обновлено"

        elif field == "courses":
            # Parse courses: Name, organization, year
            parts = [p.strip() for p in new_value.split(",")]
            update_data["courses"] = [{
                "name": parts[0] if parts else new_value,
                "organization": parts[1] if len(parts) > 1 else None,
                "completion_year": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
            }]
            field_name = "Курсы обновлены"

        elif field == "languages":
            # Parse languages: Language Level, Language Level
            languages = []
            for lang_str in new_value.split(","):
                parts = lang_str.strip().split()
                if parts:
                    lang_name = parts[0]
                    level = parts[1] if len(parts) > 1 else "B1"
                    languages.append({"language": lang_name, "level": level})
            update_data["languages"] = languages
            field_name = f"Языки обновлены ({len(languages)} шт.)"

        else:
            await message.answer("❌ Неизвестное поле для редактирования")
            await state.clear()
            return

        # Update via API
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = await build_auth_headers(message.from_user.id, state)
            if not headers:
                await message.answer("❌ Нет авторизации. Используй /start")
                return
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}",
                json=update_data,
                headers=headers
            )

            if response.status_code == 200:
                # Show continue prompt
                text = (
                    f"✅ {field_name}\n\n"
                    "<b>Ещё что-то хочешь исправить?</b>\n"
                    "Выбери раздел или нажми «Готово»:"
                )
                await message.answer(text, reply_markup=get_edit_sections_keyboard(resume_id))
                await state.set_state(ResumeEditStates.select_section)
                logger.info(f"Resume {resume_id} field '{field}' updated")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await message.answer(f"❌ Ошибка обновления: {error_detail}")
                await state.clear()

    except Exception as e:
        logger.error(f"Error updating resume field: {e}")
        await message.answer("❌ Произошла ошибка при обновлении резюме")
        await state.clear()


@router.callback_query(F.data.startswith("resume:stats:"))
async def show_resume_statistics(callback: CallbackQuery, state: FSMContext):
    """Показать подробную статистику резюме."""
    await callback.answer()
    resume_id = callback.data.split(":")[-1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = await build_auth_headers(callback.from_user.id, state)
            if not headers:
                await callback.message.answer("❌ Нет авторизации. Используйте /start")
                return

            resume_response = await client.get(f"{settings.api_url}/resumes/{resume_id}", headers=headers)
            if resume_response.status_code != 200:
                await callback.message.answer("❌ Резюме не найдено")
                return
            resume = resume_response.json()

            analytics_response = await client.get(f"{settings.api_url}/analytics/resume/{resume_id}", headers=headers)
            analytics = analytics_response.json() if analytics_response.status_code == 200 else {}

        text = format_resume_statistics(resume, analytics)

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад к резюме", callback_data=f"resume:view:{resume_id}"))

        await edit_message_content(callback, text, reply_markup=builder.as_markup())

    except httpx.TimeoutException:
        await callback.message.answer("⏱ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Error fetching resume statistics: {e}")
        await callback.message.answer("❌ Ошибка при загрузке статистики")


# Добавлена реализация функции
def format_resume_statistics(resume: dict, analytics: dict) -> str:
    """Сформировать текст подробной статистики резюме."""
    views = analytics.get("views_count", resume.get("views_count", 0))
    responses_count = analytics.get("responses_count", resume.get("responses_count", 0))
    applications = analytics.get("applications_count", 0)
    invitations = analytics.get("invitations_count", 0)
    invitation_rate = analytics.get("invitation_rate", 0)
    success_rate = analytics.get("success_rate", 0)
    days_active = analytics.get("days_active")

    responses_by_status = analytics.get("responses_by_status", {})

    lines = []
    lines.append("📊 <b>СТАТИСТИКА РЕЗЮМЕ</b>")
    lines.append(f"💼 Должность: <b>{resume.get('desired_position', 'Не указано')}</b>")
    lines.append(f"👤 ФИО: {resume.get('full_name', 'Не указано')}")
    if days_active is not None:
        lines.append(f"📅 Активно дней: {days_active}")

    lines.append("\n📈 <b>ОСНОВНЫЕ ПОКАЗАТЕЛИ</b>")
    lines.append(f"👁 Просмотры: {views}")
    lines.append(f"📬 Отклики (всего): {responses_count}")
    lines.append(f"📝 Заявки: {applications}")
    lines.append(f"✅ Приглашения: {invitations}")
    if views > 0:
        conv = (responses_count / views) * 100 if views else 0
        lines.append(f"📊 Конверсия просмотров в отклики: {conv:.1f}%")
    lines.append(f"🎯 Приглашения / просмотры: {invitation_rate:.1f}%")
    lines.append(f"🏆 Успешность (accepted/total): {success_rate:.1f}%")

    if responses_by_status:
        lines.append("\n📬 <b>Статусы откликов</b>")
        status_emoji = {
            "pending": "⏳",
            "viewed": "👀",
            "invited": "✅",
            "accepted": "🎉",
            "rejected": "❌"
        }
        for status, count in responses_by_status.items():
            emoji = status_emoji.get(status, "📝")
            lines.append(f"{emoji} {status}: {count}")

    # Период публикации
    pub = resume.get("published_at")
    if pub:
        try:
            if isinstance(pub, str):
                pub_dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
            else:
                pub_dt = pub
            # Приводим к UTC-aware и считаем по датам (без часов), чтобы на следующий день было 1
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            days = (now_utc.date() - pub_dt.astimezone(timezone.utc).date()).days
            lines.append(f"\n🗓 Опубликовано: {days} дн. назад")
        except Exception:
            pass

    # Рекомендации
    lines.append("\n💡 <b>РЕКОМЕНДАЦИИ</b>")
    if views < 10:
        lines.append("• Добавьте больше навыков и опыта")
        lines.append("• Проверьте корректность должности")
    elif views >= 10 and responses_count == 0:
        lines.append("• Уточните должность и специализацию")
        lines.append("• Проверьте контакты")
    elif views >= 20 and success_rate < 5:
        lines.append("• Улучшите описание навыков")
        lines.append("• Добавьте курсы, сертификаты")
    else:
        lines.append("✅ Резюме показывает хорошие показатели")

    return "\n".join(lines)
