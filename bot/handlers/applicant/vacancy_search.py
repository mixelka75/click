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
    logger.info(f"HANDLER: start_vacancy_search called by {message.from_user.id}")
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or not user.has_role(UserRole.APPLICANT):
        await message.answer("Эта функция доступна только для соискателей.")
        return

    logger.info(f"User {telegram_id} started vacancy search")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 По категории", callback_data="search_method:category")],
        [InlineKeyboardButton(text="🔎 Поиск по тексту", callback_data="search_method:text")],
        [InlineKeyboardButton(text="📋 Все вакансии", callback_data="search_method:all")],
        [InlineKeyboardButton(text="🔧 Фильтры", callback_data="search_filters:show")]
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
        from backend.models import Vacancy
        from datetime import datetime
        from shared.constants import VacancyStatus

        # Build MongoDB query
        query = {
            "status": VacancyStatus.ACTIVE,
            "is_published": True,
            "expires_at": {"$gt": datetime.utcnow()}
        }

        # Add search filters
        if "q" in search_params:
            # Full-text search
            q = search_params["q"]
            query["$or"] = [
                {"position": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
            ]

        if "position" in search_params:
            query["position"] = {"$regex": search_params["position"], "$options": "i"}

        if "category" in search_params:
            query["position_category"] = search_params["category"]

        if "city" in search_params:
            query["city"] = {"$regex": search_params["city"], "$options": "i"}

        # Salary filters
        if "salary_min" in search_params or "salary_max" in search_params:
            salary_query = {}
            if "salary_min" in search_params:
                # Vacancy salary_max should be >= user's min requirement
                salary_query["$gte"] = search_params["salary_min"]
            if "salary_max" in search_params:
                # Vacancy salary_min should be <= user's max requirement
                salary_query["$lte"] = search_params["salary_max"]

            if salary_query:
                query["$or"] = [
                    {"salary_max": salary_query},
                    {"salary_min": salary_query}
                ]

        # Schedule filter
        if "schedule" in search_params:
            query["work_schedule"] = {"$in": [search_params["schedule"]]}

        # Skills filter
        if "skills" in search_params:
            query["required_skills"] = {"$in": search_params["skills"]}

        # Get vacancies from MongoDB
        vacancies = await Vacancy.find(query).limit(20).to_list()

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
    vacancy_id = str(vacancy.id) if hasattr(vacancy, 'id') else vacancy['id']
    buttons.append([
        InlineKeyboardButton(text="📋 Подробнее", callback_data=f"vac_details:{vacancy_id}"),
        InlineKeyboardButton(text="✉️ Откликнуться", callback_data=f"vac_apply:{vacancy_id}")
    ])

    buttons.append([InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_search")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(VacancySearchStates.view_results)


def format_vacancy_card(vacancy, index: int, total: int) -> str:
    """Format vacancy information for display."""
    lines = [f"📋 <b>Вакансия {index} из {total}</b>\n"]

    position = vacancy.position if hasattr(vacancy, 'position') else vacancy.get('position')
    lines.append(f"💼 <b>{position}</b>")

    company_name = vacancy.company_name if hasattr(vacancy, 'company_name') else vacancy.get('company_name')
    is_anonymous = vacancy.is_anonymous if hasattr(vacancy, 'is_anonymous') else vacancy.get('is_anonymous')
    if company_name and not is_anonymous:
        lines.append(f"🏢 {company_name}")

    city = vacancy.city if hasattr(vacancy, 'city') else vacancy.get('city')
    if city:
        location = city
        nearest_metro = vacancy.nearest_metro if hasattr(vacancy, 'nearest_metro') else vacancy.get('nearest_metro')
        if nearest_metro:
            location += f" (🚇 {nearest_metro})"
        lines.append(f"📍 {location}")

    # Salary
    salary_min = vacancy.salary_min if hasattr(vacancy, 'salary_min') else vacancy.get('salary_min')
    salary_max = vacancy.salary_max if hasattr(vacancy, 'salary_max') else vacancy.get('salary_max')
    if salary_min or salary_max:
        salary_parts = []
        if salary_min:
            salary_parts.append(f"от {salary_min:,}")
        if salary_max:
            salary_parts.append(f"до {salary_max:,}")
        salary_str = " ".join(salary_parts) + " ₽"
        lines.append(f"💰 {salary_str}")

    # Employment type
    employment_type = vacancy.employment_type if hasattr(vacancy, 'employment_type') else vacancy.get('employment_type')
    if employment_type:
        lines.append(f"⏰ {employment_type}")

    # Requirements
    required_experience = vacancy.required_experience if hasattr(vacancy, 'required_experience') else vacancy.get('required_experience')
    if required_experience:
        lines.append(f"📊 Опыт: {required_experience}")

    # Description preview
    description = vacancy.description if hasattr(vacancy, 'description') else vacancy.get('description')
    if description:
        desc = description[:150]
        if len(description) > 150:
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
        from backend.models import Vacancy
        from beanie import PydanticObjectId

        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))

        if vacancy:
            # Increment views count
            vacancy.views_count += 1
            await vacancy.save()

            text = format_vacancy_details(vacancy)

            # Check if in favorites
            from bot.handlers.common.favorites import check_in_favorites
            telegram_id = callback.from_user.id
            in_favorites = await check_in_favorites(telegram_id, vacancy_id, "vacancy")

            # Build keyboard with favorites button
            fav_text = "⭐ Убрать из избранного" if in_favorites else "⭐ В избранное"
            fav_action = "remove" if in_favorites else "add"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✉️ Откликнуться", callback_data=f"vac_apply:{vacancy_id}")],
                [InlineKeyboardButton(text=fav_text, callback_data=f"fav:{fav_action}:vacancy:{vacancy_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
            ])

            await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer("❌ Вакансия не найдена.")

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
        from backend.models import Resume

        resumes_list = await Resume.find({"user.$id": user.id}).to_list()

        # Filter published resumes
        published_resumes = [r for r in resumes_list if r.is_published]

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
            position = resume.desired_position or "Не указана должность"
            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "не указана"
            button_text = f"📋 {position} | {salary_str} | {resume.city}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"apply_resume:{str(resume.id)}"
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


# ============================================================================
# SEARCH FILTERS
# ============================================================================

@router.callback_query(F.data == "search_filters:show")
async def show_search_filters(callback: CallbackQuery, state: FSMContext):
    """Show search filters menu."""
    await callback.answer()

    data = await state.get_data()
    filters = data.get("search_filters", {})

    # Format current filters
    filter_text = ["🔧 <b>Фильтры поиска</b>\n"]

    salary_min = filters.get("salary_min")
    salary_max = filters.get("salary_max")
    if salary_min or salary_max:
        salary_str = ""
        if salary_min:
            salary_str += f"от {salary_min:,} ₽"
        if salary_max:
            if salary_str:
                salary_str += " "
            salary_str += f"до {salary_max:,} ₽"
        filter_text.append(f"💰 Зарплата: {salary_str}")
    else:
        filter_text.append("💰 Зарплата: не установлена")

    schedule = filters.get("schedule")
    if schedule:
        filter_text.append(f"⏰ График: {schedule}")
    else:
        filter_text.append("⏰ График: не установлен")

    skills = filters.get("skills", [])
    if skills:
        filter_text.append(f"🎯 Навыки: {', '.join(skills[:3])}")
        if len(skills) > 3:
            filter_text.append(f"   и ещё {len(skills) - 3}")
    else:
        filter_text.append("🎯 Навыки: не указаны")

    city = filters.get("city")
    if city:
        filter_text.append(f"📍 Город: {city}")
    else:
        filter_text.append("📍 Город: не указан")

    text = "\n".join(filter_text)

    # Build keyboard
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💰 Зарплата", callback_data="filter:salary"),
        InlineKeyboardButton(text="⏰ График", callback_data="filter:schedule")
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Навыки", callback_data="filter:skills"),
        InlineKeyboardButton(text="📍 Город", callback_data="filter:city")
    )

    if filters:
        builder.row(
            InlineKeyboardButton(text="🔍 Поиск с фильтрами", callback_data="apply_filters"),
            InlineKeyboardButton(text="🗑 Сбросить", callback_data="clear_filters")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔍 Поиск с фильтрами", callback_data="apply_filters")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="filters:back")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "filter:salary")
async def set_salary_filter(callback: CallbackQuery, state: FSMContext):
    """Set salary filter."""
    await callback.answer()

    await callback.message.edit_text(
        "💰 <b>Фильтр по зарплате</b>\n\n"
        "Введите диапазон зарплаты в формате:\n"
        "<code>от XXXX до YYYY</code>\n\n"
        "Примеры:\n"
        "• <code>от 50000</code> - от 50 тыс.\n"
        "• <code>до 100000</code> - до 100 тыс.\n"
        "• <code>от 50000 до 100000</code> - диапазон\n\n"
        "Или отправьте \"-\" чтобы убрать фильтр"
    )
    await state.update_data(setting_filter="salary")
    await state.set_state(VacancySearchStates.enter_filter_value)


@router.callback_query(F.data == "filter:schedule")
async def set_schedule_filter(callback: CallbackQuery, state: FSMContext):
    """Set schedule filter."""
    await callback.answer()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from shared.constants import WORK_SCHEDULES

    builder = InlineKeyboardBuilder()

    # Add schedule options
    schedules = WORK_SCHEDULES[:6]  # First 6 schedules
    for schedule in schedules:
        builder.row(
            InlineKeyboardButton(text=schedule, callback_data=f"filter_schedule:{schedule}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="search_filters:show")
    )

    await callback.message.edit_text(
        "⏰ <b>Выберите график работы:</b>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("filter_schedule:"))
async def process_schedule_filter(callback: CallbackQuery, state: FSMContext):
    """Process schedule filter selection."""
    await callback.answer("Фильтр установлен!")

    schedule = callback.data.split(":", 1)[1]

    data = await state.get_data()
    filters = data.get("search_filters", {})
    filters["schedule"] = schedule
    await state.update_data(search_filters=filters)

    # Return to filters menu
    await show_search_filters(callback, state)


@router.callback_query(F.data == "filter:city")
async def set_city_filter(callback: CallbackQuery, state: FSMContext):
    """Set city filter."""
    await callback.answer()

    await callback.message.edit_text(
        "📍 <b>Фильтр по городу</b>\n\n"
        "Введите название города:\n"
        "Пример: Москва\n\n"
        "Или отправьте \"-\" чтобы убрать фильтр"
    )
    await state.update_data(setting_filter="city")
    await state.set_state(VacancySearchStates.enter_filter_value)


@router.callback_query(F.data == "filter:skills")
async def set_skills_filter(callback: CallbackQuery, state: FSMContext):
    """Set skills filter."""
    await callback.answer()

    await callback.message.edit_text(
        "🎯 <b>Фильтр по навыкам</b>\n\n"
        "Введите навыки через запятую:\n"
        "Пример: Бармен, Кофе, Английский язык\n\n"
        "Или отправьте \"-\" чтобы убрать фильтр"
    )
    await state.update_data(setting_filter="skills")
    await state.set_state(VacancySearchStates.enter_filter_value)


@router.message(VacancySearchStates.enter_filter_value)
async def process_filter_value(message: Message, state: FSMContext):
    """Process filter value input."""
    data = await state.get_data()
    filter_type = data.get("setting_filter")
    value = message.text.strip()

    filters = data.get("search_filters", {})

    if value == "-":
        # Remove filter
        if filter_type in filters:
            del filters[filter_type]
            if filter_type == "salary":
                filters.pop("salary_min", None)
                filters.pop("salary_max", None)
        await message.answer("✅ Фильтр убран")
    else:
        # Set filter
        if filter_type == "salary":
            import re
            # Parse salary range
            numbers = re.findall(r'\d+', value.replace(',', '').replace(' ', ''))
            if "от" in value.lower() and "до" in value.lower():
                if len(numbers) >= 2:
                    filters["salary_min"] = int(numbers[0])
                    filters["salary_max"] = int(numbers[1])
            elif "от" in value.lower():
                if numbers:
                    filters["salary_min"] = int(numbers[0])
                    filters.pop("salary_max", None)
            elif "до" in value.lower():
                if numbers:
                    filters["salary_max"] = int(numbers[0])
                    filters.pop("salary_min", None)
            else:
                await message.answer("❌ Неверный формат. Попробуйте еще раз:")
                return

            await message.answer("✅ Фильтр по зарплате установлен")

        elif filter_type == "city":
            filters["city"] = value
            await message.answer("✅ Фильтр по городу установлен")

        elif filter_type == "skills":
            skills = [s.strip() for s in value.split(",") if s.strip()]
            filters["skills"] = skills
            await message.answer(f"✅ Фильтр по навыкам установлен ({len(skills)} навыков)")

    await state.update_data(search_filters=filters)

    # Return to filters menu
    callback = CallbackQuery(
        id="dummy",
        from_user=message.from_user,
        chat_instance="dummy",
        data="search_filters:show",
        message=message
    )
    await show_search_filters(callback, state)


@router.callback_query(F.data == "clear_filters")
async def clear_filters(callback: CallbackQuery, state: FSMContext):
    """Clear all filters."""
    await callback.answer("Фильтры сброшены!")

    await state.update_data(search_filters={})
    await show_search_filters(callback, state)


@router.callback_query(F.data == "apply_filters")
async def apply_filters(callback: CallbackQuery, state: FSMContext):
    """Apply filters and search."""
    await callback.answer()

    data = await state.get_data()
    filters = data.get("search_filters", {})

    await callback.message.edit_text("⏳ Ищу вакансии с фильтрами...")

    # Convert filters to search params
    search_params = {}

    if filters.get("salary_min"):
        search_params["salary_min"] = filters["salary_min"]
    if filters.get("salary_max"):
        search_params["salary_max"] = filters["salary_max"]
    if filters.get("schedule"):
        search_params["schedule"] = filters["schedule"]
    if filters.get("city"):
        search_params["city"] = filters["city"]
    if filters.get("skills"):
        search_params["skills"] = filters["skills"]

    await show_vacancy_results(callback.message, state, search_params)


@router.callback_query(F.data == "filters:back")
async def filters_back(callback: CallbackQuery, state: FSMContext):
    """Go back from filters to main search menu."""
    await callback.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 По категории", callback_data="search_method:category")],
        [InlineKeyboardButton(text="🔎 Поиск по тексту", callback_data="search_method:text")],
        [InlineKeyboardButton(text="📋 Все вакансии", callback_data="search_method:all")],
        [InlineKeyboardButton(text="🔧 Фильтры", callback_data="search_filters:show")]
    ])

    await callback.message.edit_text(
        "🔍 <b>Поиск вакансий</b>\n\n"
        "Как вы хотите искать вакансии?",
        reply_markup=keyboard
    )
