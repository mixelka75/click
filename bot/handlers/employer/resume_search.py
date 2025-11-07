"""
Resume search handlers for employers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx
from datetime import datetime

from bot.states.search_states import ResumeSearchStates
from bot.keyboards.positions import get_position_categories_keyboard, get_positions_keyboard
from backend.models import User
from config.settings import settings
from shared.constants import UserRole


router = Router()


@router.message(F.text == "🔍 Найти резюме")
async def start_resume_search(message: Message, state: FSMContext):
    """Start resume search."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.EMPLOYER:
        await message.answer("Эта функция доступна только для работодателей.")
        return

    logger.info(f"User {telegram_id} started resume search")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 По категории", callback_data="resume_search_method:category")],
        [InlineKeyboardButton(text="🔎 Поиск по тексту", callback_data="resume_search_method:text")],
        [InlineKeyboardButton(text="📋 Все резюме", callback_data="resume_search_method:all")]
    ])

    await message.answer(
        "🔍 <b>Поиск резюме</b>\n\n"
        "Как вы хотите искать кандидатов?",
        reply_markup=keyboard
    )
    await state.set_state(ResumeSearchStates.select_method)


@router.callback_query(ResumeSearchStates.select_method, F.data.startswith("resume_search_method:"))
async def process_search_method(callback: CallbackQuery, state: FSMContext):
    """Process search method selection."""
    await callback.answer()

    method = callback.data.split(":")[1]
    await state.update_data(search_method=method)

    if method == "category":
        await callback.message.edit_text(
            "📂 <b>Поиск по категории</b>\n\n"
            "Выберите категорию должности:",
            reply_markup=get_position_categories_keyboard()
        )
        await state.set_state(ResumeSearchStates.select_category)

    elif method == "text":
        await callback.message.edit_text(
            "🔎 <b>Поиск по тексту</b>\n\n"
            "Введите ключевые слова для поиска:\n"
            "(например: 'официант опыт 2 года', 'повар итальянская кухня')"
        )
        await state.set_state(ResumeSearchStates.enter_query)

    elif method == "all":
        await callback.message.edit_text("⏳ Загружаю резюме...")
        await show_resume_results(callback.message, state, {})


@router.callback_query(ResumeSearchStates.select_category, F.data.startswith("position_cat:"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext):
    """Process category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(category=category)

    await callback.message.edit_text(
        "Выберите конкретную должность или нажмите 'Все в категории':",
        reply_markup=get_positions_keyboard(category, show_all_option=True)
    )
    await state.set_state(ResumeSearchStates.select_position)


@router.callback_query(ResumeSearchStates.select_position, F.data.startswith("position:"))
async def process_position_selection(callback: CallbackQuery, state: FSMContext):
    """Process position selection."""
    await callback.answer()

    position = callback.data.split(":", 1)[1]

    if position == "all":
        data = await state.get_data()
        category = data.get("category")
        await callback.message.edit_text(f"⏳ Загружаю резюме в категории...")
        await show_resume_results(callback.message, state, {"category": category})
    else:
        await state.update_data(position=position)
        await callback.message.edit_text(f"⏳ Ищу резюме для: {position}...")
        await show_resume_results(callback.message, state, {"position": position})


@router.message(ResumeSearchStates.enter_query)
async def process_text_query(message: Message, state: FSMContext):
    """Process text search query."""
    query = message.text.strip()

    if len(query) < 2:
        await message.answer(
            "❌ Запрос слишком короткий.\n"
            "Пожалуйста, введите хотя бы 2 символа:"
        )
        return

    await state.update_data(query=query)
    await message.answer(f"⏳ Ищу резюме по запросу: {query}...")
    await show_resume_results(message, state, {"q": query})


async def show_resume_results(message: Message, state: FSMContext, search_params: dict):
    """Show resume search results."""
    try:
        async with httpx.AsyncClient() as client:
            # Build API URL
            url = f"http://backend:8000{settings.api_prefix}/resumes/search"

            response = await client.get(
                url,
                params=search_params,
                timeout=10.0
            )

            if response.status_code == 200:
                resumes = response.json()

                if not resumes:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_resume_search")]
                    ])

                    await message.answer(
                        "😔 <b>Резюме не найдены</b>\n\n"
                        "По вашему запросу нет подходящих кандидатов.\n"
                        "Попробуйте изменить параметры поиска.",
                        reply_markup=keyboard
                    )
                    await state.clear()
                    return

                # Save resumes to state
                await state.update_data(resumes=resumes, current_index=0)

                # Show first resume
                await show_resume_card(message, state, 0)

            else:
                await message.answer(
                    "❌ Ошибка при поиске резюме.\n"
                    "Попробуйте позже."
                )
                await state.clear()

    except Exception as e:
        logger.error(f"Error searching resumes: {e}")
        await message.answer(
            "❌ Ошибка при поиске резюме.\n"
            "Попробуйте позже."
        )
        await state.clear()


async def show_resume_card(message: Message, state: FSMContext, index: int):
    """Show resume card with navigation."""
    data = await state.get_data()
    resumes = data.get("resumes", [])

    if index < 0 or index >= len(resumes):
        return

    resume = resumes[index]

    # Format resume card
    text = format_resume_card(resume, index + 1, len(resumes))

    # Build navigation keyboard
    buttons = []
    nav_buttons = []

    if index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"res_nav:prev:{index}"))

    if index < len(resumes) - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ След.", callback_data=f"res_nav:next:{index}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Action buttons
    buttons.append([
        InlineKeyboardButton(text="📋 Подробнее", callback_data=f"res_details:{resume['id']}")
    ])
    buttons.append([
        InlineKeyboardButton(text="✉️ Пригласить", callback_data=f"res_invite:{resume['id']}")
    ])
    buttons.append([
        InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav:add:resume:{resume['id']}")
    ])

    buttons.append([InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_resume_search")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(ResumeSearchStates.view_results)


def format_resume_card(resume: dict, index: int, total: int) -> str:
    """Format resume information for display."""
    lines = [f"📋 <b>Резюме {index} из {total}</b>\n"]

    if resume.get('full_name'):
        lines.append(f"👤 <b>{resume.get('full_name')}</b>")

    if resume.get('desired_position'):
        lines.append(f"💼 {resume.get('desired_position')}")
    if resume.get('citizenship'):
        lines.append(f"🌍 {resume.get('citizenship')}")
    if resume.get('birth_date'):
        try:
            birth_dt = datetime.strptime(resume['birth_date'], "%Y-%m-%d")
            lines.append(f"🎂 {birth_dt.strftime('%d.%m.%Y')}")
        except (ValueError, TypeError):
            lines.append(f"🎂 {resume['birth_date']}")
    if resume.get('city'):
        location = resume.get('city')
        if resume.get('ready_to_relocate'):
            location += " ✈️ (готов к переезду)"
        lines.append(f"📍 {location}")

    # Salary
    if resume.get('desired_salary'):
        lines.append(f"💰 От {resume['desired_salary']:,} ₽")

    # Experience
    if resume.get('total_experience_years'):
        years = resume['total_experience_years']
        lines.append(f"📊 Опыт: {years} лет")

    # Skills preview
    if resume.get('skills'):
        skills = ", ".join(resume['skills'][:3])
        if len(resume['skills']) > 3:
            skills += f" и ещё {len(resume['skills']) - 3}"
        lines.append(f"🎯 {skills}")

    # Languages preview
    if resume.get('languages'):
        lang_items = [
            f"{lang.get('language')} ({lang.get('level')})"
            for lang in resume['languages'][:2]
            if lang
        ]
        if lang_items:
            lang_text = ", ".join(lang_items)
            if len(resume['languages']) > 2:
                lang_text += f" и ещё {len(resume['languages']) - 2}"
            lines.append(f"🗣 {lang_text}")

    # About preview
    if resume.get('about'):
        about = resume['about'][:100]
        if len(resume['about']) > 100:
            about += "..."
        lines.append(f"\n{about}")

    # Stats
    views = resume.get('views_count', 0)
    responses = resume.get('responses_count', 0)
    lines.append(f"\n👁 {views} просмотров | 📬 {responses} откликов")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("res_nav:"))
async def process_resume_navigation(callback: CallbackQuery, state: FSMContext):
    """Handle resume navigation."""
    await callback.answer()

    parts = callback.data.split(":")
    direction = parts[1]
    current_index = int(parts[2])

    if direction == "prev":
        new_index = current_index - 1
    else:  # next
        new_index = current_index + 1

    await state.update_data(current_index=new_index)
    await callback.message.delete()
    await show_resume_card(callback.message, state, new_index)


@router.callback_query(F.data.startswith("res_details:"))
async def show_resume_details(callback: CallbackQuery, state: FSMContext):
    """Show detailed resume information."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/resumes/{resume_id}",
                timeout=10.0
            )

            if response.status_code == 200:
                resume = response.json()

                text = format_resume_details(resume)

                # Check if in favorites
                from bot.handlers.common.favorites import check_in_favorites
                telegram_id = callback.from_user.id
                in_favorites = await check_in_favorites(telegram_id, resume_id, "resume")

                # Build keyboard with favorites button
                fav_text = "⭐ Убрать из избранного" if in_favorites else "⭐ В избранное"
                fav_action = "remove" if in_favorites else "add"

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉️ Пригласить", callback_data=f"res_invite:{resume_id}")],
                    [InlineKeyboardButton(text=fav_text, callback_data=f"fav:{fav_action}:resume:{resume_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_resume_list")]
                ])

                await callback.message.answer(text, reply_markup=keyboard)
            else:
                await callback.message.answer("❌ Ошибка при загрузке резюме.")

    except Exception as e:
        logger.error(f"Error fetching resume details: {e}")
        await callback.message.answer("❌ Ошибка при загрузке резюме.")


def format_resume_details(resume: dict) -> str:
    """Format detailed resume information."""
    lines = ["📋 <b>РЕЗЮМЕ</b>\n"]

    if resume.get('full_name'):
        lines.append(f"👤 <b>{resume.get('full_name')}</b>\n")
    if resume.get('citizenship'):
        lines.append(f"🌍 Гражданство: {resume.get('citizenship')}")
    if resume.get('birth_date'):
        try:
            birth_dt = datetime.strptime(resume['birth_date'], "%Y-%m-%d")
            lines.append(f"🎂 Дата рождения: {birth_dt.strftime('%d.%m.%Y')}")
        except (ValueError, TypeError):
            lines.append(f"🎂 Дата рождения: {resume.get('birth_date')}")
    lines.append("")

    # Contact
    lines.append("<b>📞 КОНТАКТЫ</b>")
    if resume.get('phone'):
        lines.append(f"Телефон: {resume.get('phone')}")
    if resume.get('email'):
        lines.append(f"Email: {resume.get('email')}")
    if resume.get('telegram'):
        lines.append(f"Telegram: {resume.get('telegram')}")
    if resume.get('other_contacts'):
        lines.append(f"Доп. контакты: {resume.get('other_contacts')}")
    lines.append("")

    # Position
    lines.append("<b>💼 ЖЕЛАЕМАЯ ДОЛЖНОСТЬ</b>")
    lines.append(resume.get('desired_position', '-'))
    if resume.get('desired_salary'):
        lines.append(f"💰 От {resume['desired_salary']:,} руб.")
    lines.append("")

    # Location
    lines.append("<b>📍 МЕСТОПОЛОЖЕНИЕ</b>")
    lines.append(resume.get('city', '-'))
    if resume.get('ready_to_relocate'):
        lines.append("✈️ Готов к переезду")
    if resume.get('ready_for_business_trips'):
        lines.append("✈️ Готов к командировкам")
    lines.append("")

    # Work experience
    if resume.get('work_experience'):
        lines.append("<b>💼 ОПЫТ РАБОТЫ</b>")
        for exp in resume['work_experience'][:3]:
            lines.append(f"\n<b>{exp.get('company')}</b>")
            lines.append(f"{exp.get('position')}")
            if exp.get('start_date') and exp.get('end_date'):
                lines.append(f"{exp['start_date']} - {exp['end_date']}")
        lines.append("")

    # Education
    if resume.get('education'):
        lines.append("<b>🎓 ОБРАЗОВАНИЕ</b>")
        for edu in resume['education'][:2]:
            lines.append(f"• {edu.get('level')} - {edu.get('institution')}")
        lines.append("")

    # Skills
    if resume.get('skills'):
        lines.append("<b>🎯 НАВЫКИ</b>")
        skills_text = ", ".join(resume['skills'][:10])
        if len(resume['skills']) > 10:
            skills_text += f" и ещё {len(resume['skills']) - 10}"
        lines.append(skills_text)
        lines.append("")

    # Languages
    if resume.get('languages'):
        lines.append("<b>🗣 ЯЗЫКИ</b>")
        for lang in resume['languages']:
            lines.append(f"• {lang.get('language')} - {lang.get('level')}")
        lines.append("")

    # Courses
    if resume.get('courses'):
        lines.append("<b>🎓 КУРСЫ</b>")
        for course in resume['courses'][:5]:
            course_line = course.get('name', 'Курс')
            if course.get('organization'):
                course_line += f", {course['organization']}"
            if course.get('completion_year'):
                course_line += f" ({course['completion_year']})"
            lines.append(f"• {course_line}")
        lines.append("")

    # References
    if resume.get('references'):
        lines.append("<b>📇 РЕКОМЕНДАЦИИ</b>")
        for reference in resume['references'][:3]:
            ref_line = reference.get('full_name', 'Контакт')
            if reference.get('position'):
                ref_line += f", {reference['position']}"
            if reference.get('company'):
                ref_line += f", {reference['company']}"
            contact_parts = []
            if reference.get('phone'):
                contact_parts.append(reference['phone'])
            if reference.get('email'):
                contact_parts.append(reference['email'])
            if contact_parts:
                ref_line += f" — {'; '.join(contact_parts)}"
            lines.append(f"• {ref_line}")
        lines.append("")

    # About
    if resume.get('about'):
        lines.append("<b>📝 О СЕБЕ</b>")
        lines.append(resume.get('about'))

    return "\n".join(lines)


@router.callback_query(F.data == "back_to_resume_list")
async def back_to_resume_list(callback: CallbackQuery, state: FSMContext):
    """Return to resume list."""
    await callback.answer()
    await callback.message.delete()

    data = await state.get_data()
    current_index = data.get("current_index", 0)
    await show_resume_card(callback.message, state, current_index)


@router.callback_query(F.data.startswith("res_invite:"))
async def start_invitation(callback: CallbackQuery, state: FSMContext):
    """Start invitation process."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]
    await state.update_data(inviting_resume_id=resume_id)

    # Get employer's vacancies
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/vacancies/user/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                vacancies = response.json()

                # Filter active vacancies
                active_vacancies = [v for v in vacancies if v.get('status') == 'active']

                if not active_vacancies:
                    await callback.message.answer(
                        "❌ <b>Нет активных вакансий</b>\n\n"
                        "Создайте и опубликуйте вакансию, чтобы приглашать кандидатов."
                    )
                    return

                await state.update_data(employer_vacancies=active_vacancies)

                # Show vacancy selection
                buttons = []
                for vacancy in active_vacancies:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"💼 {vacancy.get('position')} ({vacancy.get('city')})",
                            callback_data=f"invite_vacancy:{vacancy['id']}"
                        )
                    ])

                buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_invite")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                await callback.message.answer(
                    "💼 <b>Выберите вакансию для приглашения:</b>",
                    reply_markup=keyboard
                )
                await state.set_state(ResumeSearchStates.select_vacancy)

    except Exception as e:
        logger.error(f"Error fetching employer vacancies: {e}")
        await callback.message.answer("❌ Ошибка при загрузке вакансий.")


@router.callback_query(ResumeSearchStates.select_vacancy, F.data.startswith("invite_vacancy:"))
async def process_vacancy_selection(callback: CallbackQuery, state: FSMContext):
    """Process vacancy selection for invitation."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]
    await state.update_data(inviting_vacancy_id=vacancy_id)

    await callback.message.edit_text(
        "✉️ <b>Сообщение кандидату</b>\n\n"
        "Напишите приглашение кандидату:\n"
        "(например, расскажите о вакансии и предложите встретиться)"
    )
    await state.set_state(ResumeSearchStates.enter_invitation_message)


@router.message(ResumeSearchStates.enter_invitation_message)
async def process_invitation_message(message: Message, state: FSMContext):
    """Process invitation message."""
    invitation_message = message.text.strip()

    if len(invitation_message) < 10:
        await message.answer(
            "❌ Сообщение слишком короткое.\n"
            "Напишите хотя бы 10 символов:"
        )
        return

    await state.update_data(invitation_message=invitation_message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_invite"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_invite")
        ]
    ])

    await message.answer(
        "📨 <b>Подтвердите приглашение</b>\n\n"
        "Отправить приглашение этому кандидату?",
        reply_markup=keyboard
    )
    await state.set_state(ResumeSearchStates.confirm_invitation)


@router.callback_query(ResumeSearchStates.confirm_invitation, F.data == "confirm_invite")
async def confirm_invitation(callback: CallbackQuery, state: FSMContext):
    """Confirm and send invitation."""
    await callback.answer("Отправляю приглашение...")

    data = await state.get_data()
    resume_id = data.get("inviting_resume_id")
    vacancy_id = data.get("inviting_vacancy_id")
    invitation_message = data.get("invitation_message")

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    try:
        async with httpx.AsyncClient() as client:
            invitation_data = {
                "employer_id": str(user.id),
                "vacancy_id": vacancy_id,
                "resume_id": resume_id,
                "invitation_message": invitation_message
            }

            response = await client.post(
                f"http://backend:8000{settings.api_prefix}/responses/invitation",
                json=invitation_data,
                timeout=10.0
            )

            if response.status_code == 201:
                await callback.message.edit_text(
                    "✅ <b>Приглашение отправлено!</b>\n\n"
                    "Кандидат получит ваше приглашение.\n"
                    "Следите за откликами в разделе 'Отклики на мои вакансии'."
                )
                logger.info(f"User {user.id} invited candidate {resume_id} to vacancy {vacancy_id}")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await callback.message.edit_text(
                    f"❌ Ошибка при отправке приглашения:\n{error_detail}"
                )

    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отправке приглашения."
        )

    await state.clear()


@router.callback_query(F.data == "cancel_invite")
async def cancel_invitation(callback: CallbackQuery, state: FSMContext):
    """Cancel invitation."""
    await callback.answer()
    await callback.message.edit_text("❌ Приглашение отменено.")
    await state.clear()


@router.callback_query(F.data == "new_resume_search")
async def new_search(callback: CallbackQuery, state: FSMContext):
    """Start new search."""
    await callback.answer()
    await state.clear()
    await start_resume_search(callback.message, state)
