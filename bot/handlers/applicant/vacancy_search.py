"""
Vacancy search handlers for applicants.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from bot.states.search_states import VacancySearchStates
from bot.keyboards.positions import get_position_categories_keyboard, get_positions_keyboard
from backend.models import User
from config.settings import settings
from shared.constants import UserRole


router = Router()


@router.message(F.text == "🔍 Найти вакансию")
async def start_vacancy_search(message: Message, state: FSMContext):
    """Start vacancy search."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.APPLICANT:
        await message.answer("Эта функция доступна только для соискателей.")
        return

    logger.info(f"User {telegram_id} started vacancy search")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 По категории", callback_data="search_method:category")],
        [InlineKeyboardButton(text="🔎 Поиск по тексту", callback_data="search_method:text")],
        [InlineKeyboardButton(text="📋 Все вакансии", callback_data="search_method:all")]
    ])

    await message.answer(
        "🔍 <b>Поиск вакансий</b>\n\n"
        "Как вы хотите искать вакансии?",
        reply_markup=keyboard
    )
    await state.set_state(VacancySearchStates.select_method)


@router.callback_query(VacancySearchStates.select_method, F.data.startswith("search_method:"))
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
        await state.set_state(VacancySearchStates.select_category)

    elif method == "text":
        await callback.message.edit_text(
            "🔎 <b>Поиск по тексту</b>\n\n"
            "Введите ключевые слова для поиска:\n"
            "(например: 'бармен опыт', 'повар итальянская кухня')"
        )
        await state.set_state(VacancySearchStates.enter_query)

    elif method == "all":
        await callback.message.edit_text("⏳ Загружаю вакансии...")
        await show_vacancy_results(callback.message, state, {})


@router.callback_query(VacancySearchStates.select_category, F.data.startswith("position_cat:"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext):
    """Process category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(category=category)

    await callback.message.edit_text(
        "Выберите конкретную должность или нажмите 'Все в категории':",
        reply_markup=get_positions_keyboard(category, show_all_option=True)
    )
    await state.set_state(VacancySearchStates.select_position)


@router.callback_query(VacancySearchStates.select_position, F.data.startswith("position:"))
async def process_position_selection(callback: CallbackQuery, state: FSMContext):
    """Process position selection."""
    await callback.answer()

    position = callback.data.split(":", 1)[1]

    if position == "all":
        data = await state.get_data()
        category = data.get("category")
        await callback.message.edit_text(f"⏳ Загружаю вакансии в категории...")
        await show_vacancy_results(callback.message, state, {"category": category})
    else:
        await state.update_data(position=position)
        await callback.message.edit_text(f"⏳ Ищу вакансии для: {position}...")
        await show_vacancy_results(callback.message, state, {"position": position})


@router.message(VacancySearchStates.enter_query)
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
    await message.answer(f"⏳ Ищу вакансии по запросу: {query}...")
    await show_vacancy_results(message, state, {"q": query})


async def show_vacancy_results(message: Message, state: FSMContext, search_params: dict):
    """Show vacancy search results."""
    try:
        async with httpx.AsyncClient() as client:
            # Build API URL
            url = f"http://backend:8000{settings.api_prefix}/vacancies/search"

            response = await client.get(
                url,
                params=search_params,
                timeout=10.0
            )

            if response.status_code == 200:
                vacancies = response.json()

                if not vacancies:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_search")]
                    ])

                    await message.answer(
                        "😔 <b>Вакансии не найдены</b>\n\n"
                        "По вашему запросу нет активных вакансий.\n"
                        "Попробуйте изменить параметры поиска.",
                        reply_markup=keyboard
                    )
                    await state.clear()
                    return

                # Save vacancies to state
                await state.update_data(vacancies=vacancies, current_index=0)

                # Show first vacancy
                await show_vacancy_card(message, state, 0)

            else:
                await message.answer(
                    "❌ Ошибка при поиске вакансий.\n"
                    "Попробуйте позже."
                )
                await state.clear()

    except Exception as e:
        logger.error(f"Error searching vacancies: {e}")
        await message.answer(
            "❌ Ошибка при поиске вакансий.\n"
            "Попробуйте позже."
        )
        await state.clear()


async def show_vacancy_card(message: Message, state: FSMContext, index: int):
    """Show vacancy card with navigation."""
    data = await state.get_data()
    vacancies = data.get("vacancies", [])

    if index < 0 or index >= len(vacancies):
        return

    vacancy = vacancies[index]

    # Format vacancy card
    text = format_vacancy_card(vacancy, index + 1, len(vacancies))

    # Build navigation keyboard
    buttons = []
    nav_buttons = []

    if index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"vac_nav:prev:{index}"))

    if index < len(vacancies) - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ След.", callback_data=f"vac_nav:next:{index}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Action buttons
    buttons.append([
        InlineKeyboardButton(text="📋 Подробнее", callback_data=f"vac_details:{vacancy['id']}"),
        InlineKeyboardButton(text="✉️ Откликнуться", callback_data=f"vac_apply:{vacancy['id']}")
    ])

    buttons.append([InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_search")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(VacancySearchStates.view_results)


def format_vacancy_card(vacancy: dict, index: int, total: int) -> str:
    """Format vacancy information for display."""
    lines = [f"📋 <b>Вакансия {index} из {total}</b>\n"]

    lines.append(f"💼 <b>{vacancy.get('position')}</b>")

    if vacancy.get('company_name') and not vacancy.get('is_anonymous'):
        lines.append(f"🏢 {vacancy.get('company_name')}")

    if vacancy.get('city'):
        location = vacancy.get('city')
        if vacancy.get('nearest_metro'):
            location += f" (🚇 {vacancy.get('nearest_metro')})"
        lines.append(f"📍 {location}")

    # Salary
    if vacancy.get('salary_min') or vacancy.get('salary_max'):
        salary_parts = []
        if vacancy.get('salary_min'):
            salary_parts.append(f"от {vacancy['salary_min']:,}")
        if vacancy.get('salary_max'):
            salary_parts.append(f"до {vacancy['salary_max']:,}")
        salary_str = " ".join(salary_parts) + " ₽"
        lines.append(f"💰 {salary_str}")

    # Employment type
    if vacancy.get('employment_type'):
        lines.append(f"⏰ {vacancy.get('employment_type')}")

    # Requirements
    if vacancy.get('required_experience'):
        lines.append(f"📊 Опыт: {vacancy.get('required_experience')}")

    # Description preview
    if vacancy.get('description'):
        desc = vacancy['description'][:150]
        if len(vacancy['description']) > 150:
            desc += "..."
        lines.append(f"\n{desc}")

    # Stats
    views = vacancy.get('views_count', 0)
    responses = vacancy.get('responses_count', 0)
    lines.append(f"\n👁 {views} просмотров | 📬 {responses} откликов")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("vac_nav:"))
async def process_vacancy_navigation(callback: CallbackQuery, state: FSMContext):
    """Handle vacancy navigation."""
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
    await show_vacancy_card(callback.message, state, new_index)


@router.callback_query(F.data.startswith("vac_details:"))
async def show_vacancy_details(callback: CallbackQuery, state: FSMContext):
    """Show detailed vacancy information."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/vacancies/{vacancy_id}",
                timeout=10.0
            )

            if response.status_code == 200:
                vacancy = response.json()

                text = format_vacancy_details(vacancy)

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉️ Откликнуться", callback_data=f"vac_apply:{vacancy_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
                ])

                await callback.message.answer(text, reply_markup=keyboard)
            else:
                await callback.message.answer("❌ Ошибка при загрузке вакансии.")

    except Exception as e:
        logger.error(f"Error fetching vacancy details: {e}")
        await callback.message.answer("❌ Ошибка при загрузке вакансии.")


def format_vacancy_details(vacancy: dict) -> str:
    """Format detailed vacancy information."""
    lines = ["📋 <b>ВАКАНСИЯ</b>\n"]

    lines.append(f"💼 <b>{vacancy.get('position')}</b>\n")

    # Company
    if not vacancy.get('is_anonymous'):
        lines.append("<b>🏢 КОМПАНИЯ</b>")
        lines.append(f"Название: {vacancy.get('company_name')}")
        if vacancy.get('company_description'):
            lines.append(f"{vacancy.get('company_description')}\n")

    # Location
    lines.append("<b>📍 МЕСТОПОЛОЖЕНИЕ</b>")
    lines.append(f"Город: {vacancy.get('city')}")
    if vacancy.get('address'):
        lines.append(f"Адрес: {vacancy.get('address')}")
    if vacancy.get('nearest_metro'):
        lines.append(f"🚇 {vacancy.get('nearest_metro')}\n")

    # Salary
    if vacancy.get('salary_min') or vacancy.get('salary_max'):
        lines.append("<b>💰 ЗАРПЛАТА</b>")
        salary_parts = []
        if vacancy.get('salary_min'):
            salary_parts.append(f"от {vacancy['salary_min']:,}")
        if vacancy.get('salary_max'):
            salary_parts.append(f"до {vacancy['salary_max']:,}")
        lines.append(" ".join(salary_parts) + " руб.\n")

    # Employment
    lines.append("<b>⏰ УСЛОВИЯ</b>")
    if vacancy.get('employment_type'):
        lines.append(f"Занятость: {vacancy.get('employment_type')}")
    if vacancy.get('work_schedule'):
        schedule = ", ".join(vacancy.get('work_schedule', []))
        lines.append(f"График: {schedule}\n")

    # Requirements
    lines.append("<b>📋 ТРЕБОВАНИЯ</b>")
    if vacancy.get('required_experience'):
        lines.append(f"• Опыт: {vacancy.get('required_experience')}")
    if vacancy.get('required_education'):
        lines.append(f"• Образование: {vacancy.get('required_education')}")
    if vacancy.get('required_skills'):
        skills = ", ".join(vacancy.get('required_skills', [])[:5])
        lines.append(f"• Навыки: {skills}\n")

    # Benefits
    if vacancy.get('benefits'):
        lines.append("<b>✨ МЫ ПРЕДЛАГАЕМ</b>")
        for benefit in vacancy.get('benefits', [])[:5]:
            lines.append(f"• {benefit}")
        lines.append("")

    # Description
    if vacancy.get('description'):
        lines.append("<b>📝 ОПИСАНИЕ</b>")
        lines.append(vacancy.get('description') + "\n")

    # Responsibilities
    if vacancy.get('responsibilities'):
        lines.append("<b>📌 ОБЯЗАННОСТИ</b>")
        for resp in vacancy.get('responsibilities', [])[:5]:
            lines.append(f"• {resp}")
        lines.append("")

    # Contact
    if not vacancy.get('is_anonymous') and vacancy.get('contact_phone'):
        lines.append("<b>📞 КОНТАКТЫ</b>")
        lines.append(f"Телефон: {vacancy.get('contact_phone')}")
        if vacancy.get('contact_email'):
            lines.append(f"Email: {vacancy.get('contact_email')}")

    return "\n".join(lines)


@router.callback_query(F.data == "back_to_list")
async def back_to_vacancy_list(callback: CallbackQuery, state: FSMContext):
    """Return to vacancy list."""
    await callback.answer()
    await callback.message.delete()

    data = await state.get_data()
    current_index = data.get("current_index", 0)
    await show_vacancy_card(callback.message, state, current_index)


@router.callback_query(F.data.startswith("vac_apply:"))
async def start_application(callback: CallbackQuery, state: FSMContext):
    """Start application process."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]
    await state.update_data(applying_vacancy_id=vacancy_id)

    # Get user's resumes
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/resumes/user/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                resumes = response.json()

                # Filter published resumes
                published_resumes = [r for r in resumes if r.get('is_published')]

                if not published_resumes:
                    await callback.message.answer(
                        "❌ <b>Нет опубликованных резюме</b>\n\n"
                        "Создайте и опубликуйте резюме, чтобы откликаться на вакансии."
                    )
                    return

                await state.update_data(user_resumes=published_resumes)

                # Show resume selection
                buttons = []
                for resume in published_resumes:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"📋 {resume.get('desired_position')} ({resume.get('city')})",
                            callback_data=f"apply_resume:{resume['id']}"
                        )
                    ])

                buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_apply")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                await callback.message.answer(
                    "📋 <b>Выберите резюме для отклика:</b>",
                    reply_markup=keyboard
                )
                await state.set_state(VacancySearchStates.select_resume)

    except Exception as e:
        logger.error(f"Error fetching user resumes: {e}")
        await callback.message.answer("❌ Ошибка при загрузке резюме.")


@router.callback_query(VacancySearchStates.select_resume, F.data.startswith("apply_resume:"))
async def process_resume_selection(callback: CallbackQuery, state: FSMContext):
    """Process resume selection for application."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]
    await state.update_data(applying_resume_id=resume_id)

    await callback.message.edit_text(
        "✉️ <b>Сопроводительное письмо</b>\n\n"
        "Напишите краткое сопроводительное письмо работодателю:\n"
        "(или отправьте '-' чтобы пропустить)"
    )
    await state.set_state(VacancySearchStates.enter_cover_letter)


@router.message(VacancySearchStates.enter_cover_letter)
async def process_cover_letter(message: Message, state: FSMContext):
    """Process cover letter."""
    cover_letter = message.text.strip()

    if cover_letter != '-':
        await state.update_data(cover_letter=cover_letter)
    else:
        await state.update_data(cover_letter=None)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_apply"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_apply")
        ]
    ])

    await message.answer(
        "📨 <b>Подтвердите отклик</b>\n\n"
        "Отправить отклик на эту вакансию?",
        reply_markup=keyboard
    )
    await state.set_state(VacancySearchStates.confirm_application)


@router.callback_query(VacancySearchStates.confirm_application, F.data == "confirm_apply")
async def confirm_application(callback: CallbackQuery, state: FSMContext):
    """Confirm and send application."""
    await callback.answer("Отправляю отклик...")

    data = await state.get_data()
    vacancy_id = data.get("applying_vacancy_id")
    resume_id = data.get("applying_resume_id")
    cover_letter = data.get("cover_letter")

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    try:
        async with httpx.AsyncClient() as client:
            response_data = {
                "applicant_id": str(user.id),
                "vacancy_id": vacancy_id,
                "resume_id": resume_id,
            }

            if cover_letter:
                response_data["cover_letter"] = cover_letter

            response = await client.post(
                f"http://backend:8000{settings.api_prefix}/responses",
                json=response_data,
                timeout=10.0
            )

            if response.status_code == 201:
                await callback.message.edit_text(
                    "✅ <b>Отклик отправлен!</b>\n\n"
                    "Ваш отклик успешно отправлен работодателю.\n"
                    "Следите за статусом в разделе 'Мои отклики'."
                )
                logger.info(f"User {user.id} applied to vacancy {vacancy_id}")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await callback.message.edit_text(
                    f"❌ Ошибка при отправке отклика:\n{error_detail}"
                )

    except Exception as e:
        logger.error(f"Error creating response: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отправке отклика."
        )

    await state.clear()


@router.callback_query(F.data == "cancel_apply")
async def cancel_application(callback: CallbackQuery, state: FSMContext):
    """Cancel application."""
    await callback.answer()
    await callback.message.edit_text("❌ Отклик отменён.")
    await state.clear()


@router.callback_query(F.data == "new_search")
async def new_search(callback: CallbackQuery, state: FSMContext):
    """Start new search."""
    await callback.answer()
    await state.clear()
    await start_vacancy_search(callback.message, state)
